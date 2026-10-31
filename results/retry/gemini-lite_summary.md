# Targeted retry on flagged receipts: gemini-lite

flagged: 20

| mode | n | fixed wrong->right | broke right->wrong | still wrong | flags cleared | code kept retry | kept answer correct |
|---|---|---|---|---|---|---|---|
| blind | 20 | 0 | 1 | 5 | 0 | 0 | 15 |
| guided | 20 | 1 | 1 | 4 | 4 | 4 | 16 |
