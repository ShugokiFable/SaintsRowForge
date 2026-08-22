# Lua / Script Research Notes

## Primary source

Kinzie's Toy Box contains Volition-generated SRTT script-action documentation, including a large index and individual action pages. This should be treated as the best public baseline for function names/signatures, but not blindly as SRIV truth.

## SRIV caution

Community SRIV scripting references note that many SRTT calls carry over but arguments/availability can differ. A commonly documented difference is use of `LOCAL_PLAYER` and `REMOTE_PLAYER` in SRIV-oriented examples.

## Safe Forge feature ideas

- Build a local searchable function-name/signature index from fetched official documentation.
- Scan extracted vanilla `.lua` files to learn which functions are actually used by the installed game.
- Lint calls against game-specific observations.
- Keep execution separate from lint/indexing.

## Re-Elected

SaintExec is explicitly a Re-Elected-era project. Keep its API/injection assumptions in a separate compatibility bucket so the legacy SRIV Forge never learns incorrect runtime assumptions from it.
