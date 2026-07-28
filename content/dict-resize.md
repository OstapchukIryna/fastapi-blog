Everyone knows a dict lookup is O(1) on average. Fewer people can say what
happens on the write that pushes it over the edge.

## The trigger

CPython resizes when the table is about two-thirds full. In C the check is
essentially `used * 3 >= size * 2`. Two-thirds is a deliberate compromise:
lower means wasted memory, higher means collisions climb sharply.

## The new size

Not "a bit bigger". The target is `used * 3` rounded up to the next power of
two, and the calculation uses **used**, not the current allocation. That
detail matters — a dict that had many keys deleted can shrink on its next
resize rather than grow.

Powers of two are not decorative either. The index is computed with a mask
rather than a modulo, and masking only works when the size is a power of two.

## What it costs

Everything is rehashed. Old slots are not copied across, because the mask
changed and every key now maps somewhere else. So one unlucky insert pays for
the whole table.

Amortised over all the inserts it is still O(1). For a single insert in a hot
loop it is not, which is why pre-sizing matters when the final count is known.

The part I had wrong for a while: I assumed collisions were resolved by
chaining. CPython uses open addressing throughout — no linked lists, no extra
allocations, and probing that is deliberately pseudo-random rather than linear
so that clusters do not form.