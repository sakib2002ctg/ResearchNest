# Reference manager boundaries

All private operations derive ownership from the authenticated principal and
filter SQL by `Citation.user_id`. Creation, editing, import and deletion share
the durable per-user database lock with writing mutations. DOI identity and
normalized title/year deduplicate within one tenant. Stable `cite_key` values
cannot be renamed because saved Markdown/version snapshots may reference them.

POST accepts manual metadata, an owned `UserPaper.id`, or a DOI-only lookup.
Library lookup first proves ownership, then reads global academic metadata.
If an existing reference matches and has no library link, saving from a paper
attaches that owned paper without replacing manually edited metadata. Existing
non-null library links are preserved. Deleting a library paper clears the link,
while keeping the user's bibliographic record.

An entry may be incomplete and remains visibly unverified. Required metadata
checks produce warnings for missing authors, year or venue/DOI. Manual/imported
records are never provider verified. Academic-provider or canonical metadata
can be verified only with complete identifying fields and trusted provenance;
client overrides or additions revoke that status. A verification flag cannot
be supplied by the client. Verification means metadata provenance, not proof
of scientific claims, a publication's quality, or correctness of every detail.

Formatting produces deterministic plain-text common templates for APA 7,
IEEE, MLA 9, Chicago author-date and a common Harvard author-date variant.
IEEE numbering follows requested reference order. MLA omits a page locator
when none was supplied rather than inventing one. Rich-text italics, complex
name particles/corporate-author parsing, source categories beyond the supported
schema and institutional style variants require manual review. Source guidance:

- [APA reference examples](https://apastyle.apa.org/style-grammar-guidelines/references/examples)
- [IEEE reference guide](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf)
- [MLA reference guidance](https://style.mla.org/works-cited/citations-by-format/)

BibTeX/RIS import accepts at most 200 entries and 500,000 characters per request.
The parser validates all records before committing any. BibTeX macros, preambles
and concatenation are rejected; no TeX is evaluated. Ordinary braces, quoted
values, repeated RIS authors and date/page fields are supported. BibTeX exports
escape TeX metacharacters; RIS metadata excludes line/control-character injection.
Citation exports include selected owned IDs or all owned references up to 2,000;
oversized exports fail explicitly instead of silently truncating. Downloads use
generated attachment names and `private, no-store` / `nosniff` headers.
