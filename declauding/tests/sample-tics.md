# Does a budget-exact quant cost accuracy?

## The question

So: does solving for the budget cost you anything? A mix chosen to fill a number is a different object from a recipe chosen for quality.

## The setup

Six legs. One GPU, one server build, one sampler, one question set.

Nobody had checked whether it could still think. It is the leg that answers the actual question.

One thing is not flat, and the table shows it. That is the variable the fits exist to test.

fit-17g is the exception in both directions. Its row is not a test of long context — it is a test of what 2.876 bits per weight does to the model's reasoning.

## Where the misses go

Five of those six rows are one cluster. The sixth is not.

## What "exhausted" means

It is not a wrong answer. It is a non-answer. Counting it as a failure is the conservative choice, and it is what these numbers do.

The same questions exhaust in every leg.

When only the fits had run, that looked like it might be a property of the fits. It isn't.

So the failure mode is not mostly about the quantization. It is mostly about the question. The two failure modes also live in different places.

## The one gap that does clear the bar

Here is what the same instrument looks like when it can resolve a difference.

So how does it fail?

Mostly by not finishing.

"It thinks twice as long" is the obvious reading of that, and it is wrong.

That is what the data shows.

Median hides it: the middle of every distribution is similar.

## An earlier baseline that did not count

The detail that makes the point: in that older config the higher-precision KV cache scored lower. Not because f16 KV hurts — because a comparison across four simultaneous changes carries no information about any one of them. It is the kind of number that looks like evidence and is not.

It is not a method; it is a lucky escape.

## Method notes

Everything below is the inference side, which is the part that transfers. --calibrate is the part that matters.

A distinction worth keeping separate: a metric can fail two different ways. Their phrasing for it is better than mine.
