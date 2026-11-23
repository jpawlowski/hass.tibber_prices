## What Tibber Prices does

It brings Tibber's electricity prices into Home Assistant, so people can:

- see the current price and what comes next on their dashboard
- run the dishwasher, washing machine, heat pump or EV charging in the cheapest hours
- get told when prices are unusually high or low
- find the best window in the day for a load that can wait

Write for someone who pays the bill, not for someone who reads the code.

## Words to keep out of the notes

These are names from the code. Describe what the user sees instead:
`interval_pool`, `BaseCalculator`, coordinator, period calculation internals, `price_info` and other attribute or
module names, cache, pool and iterator.

## Commit trailers

A commit body may carry an `Impact:` line. It is the author's own user-facing description: prefer it over the commit
subject.

## Title

Start the notes with one `#` heading of at most six words that names the change users will notice most, such as
"Reliable prices around clock changes". No version number, no exclamation mark. Choose by what users notice: new
sensors, then fixes to wrong data, then reliability, then display, then translations.

## Voice

On top of the rules above:

- "You" for the reader. Never "one" or "the user".
- No list of three out of habit when two things are true. Use "not X but Y" at most once in the whole text.
- No colon that reveals a punchline ("The result: fewer errors").
- Dashes sparingly. The section emojis are enough; no emojis in the text.
- A fix is told as what was wrong and is now right, without apologizing and without blaming anyone.
