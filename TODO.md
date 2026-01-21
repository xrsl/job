# application cmd (alias app)

Keep the <id> positional everywhere to be consistent.

job app ls # list all applications in db
job app write 42 # might also be just callback, so job app 42, similar to job fit 42, createsDraftResult
job app tag 42 # Tag application as final, might also named submit
job app view 42
job app rm 42 # Remove application

--cv/--no-cv
--letter/--no-letter
--render -r/--no-render # default false, calls typst

job app w <id> -m <model> --source src/cv.toml --source src/letter.toml --template src/template.toml
job app w <id> --no-letter # validates and formats using cue? or just rely on pydantic-ai
job app r <id> # render the application for job 42, uses renderer, template, and output flags
job app t <id> # tag the current state of the application for job <id>, makes it final
job app v <id> # view application made (tagged) for job

[job.app]
model = "gpt-4o"
schema = "schema/schema.json"
renderer = "typst"

[job.app.documents.cv]
source = "src/cv.toml"
template = "template/cv.typ"
output = "out/cv.pdf"

[job.app.documents.letter]
source = "src/letter.toml"
schema = "schema/letter.json"
template = "template/letter.typ"
output = "out/letter.pdf"

# fit

Keep the <id> positional everywhere to be consistent.
rename context to extra
[job.fit]
cv = "src/cv.toml"
extra = ["persona.md", "experience.md"]
j

job fit --cv cv.pdf --extra persona.md
