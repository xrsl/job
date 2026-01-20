package job

#CareerPage: {
	company: string
	url:     string
	keywords?: [...string]
	enabled?: bool | *true
}

#JobSearch: {
	keywords: [...string]
	in: [...#CareerPage]
}

job: {
	search: #JobSearch
}
