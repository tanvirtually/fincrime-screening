# Namesake

Namesake reviews sanctions screening alerts automatically. For each watchlist hit, it checks the bank's customer records and decides whether the listed person is the **same person** as the customer, a **different person**, or **needs a human** to review. Each decision comes with a short reason and the records it used.

It only clears a hit when a fact rules it out. Anything uncertain goes to a person.

Built for Track 2 ("Is my customer sanctioned?") of the London Financial Crime Hackathon.

## Results on the development set

- 50 out of 50 practice cases right, with no wrong clearances
- 819 hits decided in about 6 seconds
- Python standard library only: no AI model, no internet, no cost
- Same answer every run, and the same decisions when the data is reworded

## Run it

```
system/run <data folder> <output file>
```

For example: `system/run dev output/dev.jsonl`

## Where things are

| | |
|---|---|
| [`system/README.md`](system/README.md) | How it works, in plain language, with three worked examples |
| [`system/`](system/) | The system |
| [`output/dev.jsonl`](output/dev.jsonl) | Its decisions on the development set |
| [`tests/`](tests/) | Output and name-matching tests (run on every push) |

The organisers' dataset is not included in this repository.
