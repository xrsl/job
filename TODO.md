# application cmd (alias app)

implement sub app named app_app in job/app.py and add it into main similar to fit_app.
it will write docs with ai similar to cvx build (see ../cvx/)

Keep the <id> positional everywhere to be consistent.

job app ls # list all applications in db
job app write 42 # might also be just callback, so job app 42, similar to job fit run 42, creates DraftResult
--cv/--no-cv
--letter/--no-letter
job app view 42 -i 1 # view application made for job
job app rm 42 # Remove all DraftResult for 42 application

DraftResult has id, job_id, all the ai written src files content? and other metadata similar to AssessmentResult
1 job can have multiple DraftResults from different models and different sources, can also be diffs.

job app w <id> -m <model> --source src/cv.toml --source src/letter.toml --template src/template.toml
job app w <id> --no-letter # validates and formats using cue? or just rely on pydantic-ai
job app v <id> -i 1 # view application made for job

[job.app]
model = "gpt-4o"
schema = "schema/schema.json"

[job.app.write.cv]
source = "src/cv.toml"

[job.app.write.letter]
source = "src/letter.toml"
schema = "schema/letter.json"

output = "out/letter.pdf"
output = "out/cv.pdf"
job app tag 42 # Tag application as final, might also named submit
job app t <id> # tag the current state of the application for job <id>, makes it final
--render -r/--no-render # default false, calls typst
template = "template/cv.typ"
template = "template/letter.typ"
renderer = "typst"
job app r <id> # render the application for job 42, uses renderer, template, and output flags
