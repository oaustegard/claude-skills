# capturing-browser-logs

Gets runtime evidence from a web page the agent cannot run itself, using [Agent Log](https://austegard.com/web-utilities/agent-log.html): a script that records console calls, errors and fetch/XHR traffic as OpenTelemetry logs in the user's browser. The skill tells the agent how to have the user turn logging on (query parameter, bookmarklet or console paste), how to add structured `console.log` calls, and how to read and filter the OTLP/JSON export with a bundled Python reader.
