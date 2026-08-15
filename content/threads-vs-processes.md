I had twelve images to download and process. The download part was slow, so I
threw threads at it and the runtime dropped by a factor of four. Encouraged, I
threw threads at the processing part too. Nothing happened. Then I switched
that half to processes, and it got faster.

That gap is the whole lesson, and I only understood it after I had the numbers
in front of me.

## What I expected

I expected concurrency to be one thing. You have work, you split it across
workers, it finishes sooner. Under that model both halves of the script should
have behaved the same way, and the only question was how many workers to use.

## What actually happened

| stage | sequential | threads | processes |
| --- | --- | --- | --- |
| download | 8.4s | 2.1s | 2.6s |
| edge detection | 11.2s | 11.0s | 3.1s |


Threads did nothing for the second row. Processes were *slower* for the first.
Two tools, two opposite outcomes, same machine.

## Why

The answer is the GIL, but not in the way it usually gets repeated. The GIL
prevents two threads from executing Python bytecode at the same time. It does
not prevent a thread from **waiting**.

When a thread makes a blocking network call, CPython releases the GIL before
handing control to the operating system:

```python
async with semaphore:
    response = await client.get(url, timeout=10)
    response.raise_for_status()
```

While that request is in flight, the lock sits unheld. Every other thread is
free to run — and typically goes straight into its own wait. Twelve downloads
spend almost all their time doing nothing, so they overlap almost perfectly.

Edge detection has no waiting in it at all. It is a loop over pixels, which
means it holds the GIL continuously. Adding threads adds context switching and
nothing else.

> Threads and processes are not two speeds of the same thing. They solve
> different kinds of blocking.

Processes sidestep the lock entirely, because each one is a separate
interpreter with its own GIL. That is why the second row moved. It is also why
the first row got worse: `spawn` has to start a fresh interpreter, and the
result has to be pickled back across a pipe. For a few megabytes of image data
that cost is real.

## The rule I use now

- Work that **waits** — network, disk, database — goes to `asyncio` or threads.
- Work that **computes** — parsing, image processing, number crunching — goes
  to `ProcessPoolExecutor`.
- If the answer is not obvious, measure both. It takes ten minutes and settles
  the question permanently.

---

The part I keep coming back to is that I could have read this explanation a
dozen times and still not held onto it. Watching threads refuse to help, and
then watching processes help, made it stick in an afternoon.
