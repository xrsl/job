package job

// Career page configuration for job search
#CareerPage: {
	company: string
	url:     string
	keywords?: [...string]
	"extra-keywords"?: [...string]
	enabled?: bool | *true
}

// Job search configuration
#JobSearch: {
	keywords: [...string]
	parallel?: bool
	since?:    int
	in: [...#CareerPage]
}

// GitHub integration settings
#JobGH: {
	repo?: string
	"default-labels"?: [...string]
	"auto-assign"?: bool | *false
}

// Fit assessment settings
#JobFit: {
	cv?:    string
	model?: string
	extra?: [...string]
}

// Add command settings
#JobAdd: {
	structured?: bool | *false
	browser?:    bool | *false
	model?:      string
}

// Export command settings
#JobExport: {
	"output-format"?: string | *"json"
	output?:          string
}

// App command settings
#JobApp: {
	model?:  string
	schema?: string
	cv?:     string
	letter?: string
}

// Top-level job settings
#JobSettings: {
	model?:     string
	verbose?:   bool | *false
	"db-path"?: string

	gh?:     #JobGH
	fit?:    #JobFit
	add?:    #JobAdd
	app?:    #JobApp
	export?: #JobExport
	search?: #JobSearch
}

// Root configuration schema
job: #JobSettings
