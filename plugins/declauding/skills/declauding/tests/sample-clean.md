# A few words on DS4

I didn't expect DwarfStar 4 to become so popular so fast. It is clear that there was a need for single-model integration focused local AI experience, and that a few things happened together: the release of a quasi-frontier model that is large and fast enough to change the game of local inference, and the fact that it works extremely well with an extremely asymmetric quants recipe of 2/8 bit, so that 96 or 128GB of RAM are enough to run it.

The last week was funny and also tiring, I worked 14 hours per day on average. My normal average is 4/6 since early Redis times, but the first few months of Redis were like that.

So, what's next? Is this a project that starts and ends with DeepSeek v4 Flash? Nope, the model can change over time. The space will be occupied, in my vision, by the best current open weights model that is practically fast on a high end Mac or GPU in a box gear.

## Power capping

Long local inference runs can keep the GPU busy for extended periods. If you care more about heat, fan noise, battery life on MacBooks, or reducing thermal stress on the hardware than about maximum throughput, use --power N. --power 100 is the default and means full speed. Lower values ask DwarfStar to target that percentage of GPU usage. DwarfStar does this by measuring GPU work time and inserting small sleeps between work units: during prefill it sleeps between layers, and during generation it sleeps between decoded tokens. This reduces sustained load without changing model output.

I did not expect the overlap to survive a 3x range in bits per weight and two different quant families.

"You took eleven seconds," Sonnet said.

"I know."

"On four sentences."

"Then take twelve."
