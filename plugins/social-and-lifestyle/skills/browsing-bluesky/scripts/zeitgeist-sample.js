#!/usr/bin/env node
/**
 * Bluesky Zeitgeist Sampler
 * Samples firehose for N seconds, outputs structured JSON for analysis
 */

// Ensure node_modules installed in home directory are resolvable regardless
// of the working directory this script is invoked from (fixes #271)
const path = require('path');
const homeDir = process.env.HOME || '/home/claude';
module.paths.unshift(path.join(homeDir, 'node_modules'));

const WebSocket = require('ws');
const { HttpsProxyAgent } = require('https-proxy-agent');

const JETSTREAM_URL = 'wss://jetstream1.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post';
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY;

const STOPWORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'must', 'and', 'but', 'or', 'for', 'to',
  'of', 'in', 'on', 'at', 'by', 'with', 'from', 'this', 'that', 'it',
  'i', 'you', 'he', 'she', 'we', 'they', 'my', 'your', 'his', 'her',
  'its', 'our', 'their', 'me', 'him', 'us', 'them', 'what', 'which',
  'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
  'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
  'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here',
  'https', 'http', 'www', 'com', 'org', 'net', 'bsky', 'social',
  'lol', 'lmao', 'omg', 'gonna', 'gotta', 'wanna', 'yeah', 'yes', 'nope',
  'really', 'actually', 'literally', 'like', 'think', 'know', 'get', 'got',
  'going', 'want', 'need', 'see', 'look', 'come', 'make', 'take', 'give',
  'today', 'yesterday', 'tomorrow', 'tonight', 'morning', 'night', 'day',
  'week', 'month', 'year', 'time', 'now', 'still', 'already', 'always',
  'good', 'bad', 'great', 'best', 'better', 'much', 'many', 'well',
  'thing', 'things', 'something', 'anything', 'everything', 'nothing',
  'one', 'two', 'first', 'last', 'new', 'old', 'right', 'way', 'back',
  'people', 'person', 'man', 'woman', 'lot', 'bit', 'feel', 'love',
  'post', 'posted', 'thread', 'quote', 'reply', 'repost',
]);

class ZeitgeistSampler {
  constructor(duration = 10, filter = null) {
    this.duration = duration;
    this.filter = filter ? filter.toLowerCase() : null;
    this.posts = [];
    this.wordFreq = {};
    this.bigramFreq = {};
    this.trigramFreq = {};
    this.stats = { received: 0, filtered: 0, startTime: null, endTime: null, langs: {} };
  }

  tokenize(text) {
    return text
      .toLowerCase()
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[^\w\s'-]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 2 && !STOPWORDS.has(w) && !/^\d+$/.test(w));
  }

  processPost(text, altTexts = []) {
    // Combine post text with any image alt texts
    const fullText = [text, ...altTexts].join(' ');
    const words = this.tokenize(fullText);
    
    for (const word of words) {
      this.wordFreq[word] = (this.wordFreq[word] || 0) + 1;
    }
    
    for (let i = 0; i < words.length - 1; i++) {
      const bigram = `${words[i]} ${words[i + 1]}`;
      this.bigramFreq[bigram] = (this.bigramFreq[bigram] || 0) + 1;
    }
    
    for (let i = 0; i < words.length - 2; i++) {
      const trigram = `${words[i]} ${words[i + 1]} ${words[i + 2]}`;
      this.trigramFreq[trigram] = (this.trigramFreq[trigram] || 0) + 1;
    }
  }

  async sample() {
    return new Promise((resolve, reject) => {
      const filterMsg = this.filter ? ` (filtering for "${this.filter}")` : '';
      console.error(`Sampling ${this.duration}s${filterMsg}...`);
      
      const wsOptions = proxyUrl ? { agent: new HttpsProxyAgent(proxyUrl) } : {};
      const ws = new WebSocket(JETSTREAM_URL, wsOptions);
      this.stats.startTime = Date.now();
      
      const timeout = setTimeout(() => {
        ws.close();
        this.stats.endTime = Date.now();
        resolve(this.analyze());
      }, this.duration * 1000);

      ws.on('open', () => {
        console.error(`Connected`);
      });

      ws.on('message', (data) => {
        try {
          const event = JSON.parse(data.toString());
          if (event.kind !== 'commit') return;
          if (event.commit?.collection !== 'app.bsky.feed.post') return;
          if (event.commit?.operation !== 'create') return;
          
          const record = event.commit?.record;
          const text = record?.text;
          if (!text) return;
          
          // Extract alt texts from embedded images
          const altTexts = [];
          if (record?.embed?.images) {
            for (const img of record.embed.images) {
              if (img.alt) altTexts.push(img.alt);
            }
          }
          
          this.stats.received++;
          
          // Apply filter if specified
          if (this.filter) {
            const fullText = [text, ...altTexts].join(' ').toLowerCase();
            if (!fullText.includes(this.filter)) return;
            this.stats.filtered++;
          }
          
          this.posts.push({ 
            text, 
            altTexts,
            langs: record?.langs || [],
            hasImages: !!record?.embed?.images?.length 
          });
          this.processPost(text, altTexts);
          
          for (const lang of (record?.langs || [])) {
            this.stats.langs[lang] = (this.stats.langs[lang] || 0) + 1;
          }
          
          if (this.posts.length % 50 === 0) {
            console.error(`  ${this.posts.length} matching posts (${this.stats.received} total)...`);
          }
        } catch (e) {}
      });

      ws.on('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });

      ws.on('close', () => {
        clearTimeout(timeout);
        this.stats.endTime = Date.now();
        resolve(this.analyze());
      });
    });
  }

  analyze() {
    const elapsed = (this.stats.endTime - this.stats.startTime) / 1000;
    
    const topWords = Object.entries(this.wordFreq)
      .filter(([_, n]) => n >= 3)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 50);
    
    const topPhrases = Object.entries(this.bigramFreq)
      .filter(([_, n]) => n >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 30);
    
    const topTrigrams = Object.entries(this.trigramFreq)
      .filter(([_, n]) => n >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20);
    
    // Detect named entities via capitalization patterns
    const entities = {};
    for (const post of this.posts) {
      const matches = post.text.match(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/g) || [];
      for (const m of matches) {
        if (!['The', 'This', 'That', 'What', 'When', 'Where', 'Just', 'And', 'But'].some(s => m.startsWith(s))) {
          entities[m] = (entities[m] || 0) + 1;
        }
      }
    }
    const topEntities = Object.entries(entities)
      .filter(([_, n]) => n >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 25);
    
    // Sample posts (for display)
    const samplePosts = this.posts.slice(0, 50).map(p => ({
      text: p.text,
      altTexts: p.altTexts,
      hasImages: p.hasImages
    }));
    
    return {
      window: {
        startTime: new Date(this.stats.startTime).toISOString(),
        endTime: new Date(this.stats.endTime).toISOString(),
        durationSeconds: elapsed
      },
      stats: {
        totalReceived: this.stats.received,
        totalPosts: this.posts.length,
        postsPerSecond: parseFloat((this.posts.length / elapsed).toFixed(1)),
        filter: this.filter || null,
        languages: this.stats.langs
      },
      topWords,
      topPhrases,
      topTrigrams,
      entities: topEntities,
      samplePosts
    };
  }
}

async function main() {
  const args = process.argv.slice(2);
  let duration = 10;
  let filter = null;
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--duration' || args[i] === '-d') {
      duration = parseInt(args[++i]) || 10;
    } else if (args[i] === '--filter' || args[i] === '-f') {
      filter = args[++i];
    } else if (args[i] === '--help' || args[i] === '-h') {
      console.log(`Usage: node zeitgeist-sample.js [options]
Options:
  -d, --duration N   Sample for N seconds (default: 10)
  -f, --filter TERM  Only capture posts containing TERM`);
      process.exit(0);
    }
  }
  
  const sampler = new ZeitgeistSampler(duration, filter);
  
  try {
    const results = await sampler.sample();
    console.log(JSON.stringify(results, null, 2));
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

main();
