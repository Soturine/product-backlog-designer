# /pbd-diff

`pbd evolve diff --old <dir with previous versions> --new <dir with new versions> --source <selector> ... --out evo/` compares the selected sources member by member after the same text extraction readers use. Each member is `identical`, `formatting_only` (equal after whitespace/case/punctuation normalisation: an administrative change), `content` (with line hunks), `added` or `removed`. The runtime never decides what a content change means: read the new version as a reader would and decide in an evolution proposal ([/pbd-adr](adr.md)).
