# application cmd (alias app)


job app w 1 -s schema.json should enforce ai to conform to user-provided schema which can have defs of cv and letter.

output = "out/letter.pdf"
output = "out/cv.pdf"
job app tag 42 # Tag application as final, might also named submit
job app t <id> # tag the current state of the application for job <id>, makes it final
--render -r/--no-render # default false, calls typst
template = "template/cv.typ"
template = "template/letter.typ"
renderer = "typst"
job app r <id> # render the application for job 42, uses renderer, template, and output flags
