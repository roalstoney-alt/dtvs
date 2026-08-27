# Chinese subtitle preparation

`inputs/subtitles_zh.srt` is a controlled Pilot input, not an output generated silently by the pipeline.

Minimum checks:

- UTF-8 encoding;
- source/translator and rights note recorded;
- cue numbers ordered;
- timestamps monotonically increasing and within source duration;
- names and technical terms reviewed consistently;
- intertitles translated without inventing dialogue;
- timing checked against the exact source master;
- full file SHA-256 captured before execution.

For a silent-film source, subtitle cues normally translate intertitles rather than create a continuous dialogue track.

