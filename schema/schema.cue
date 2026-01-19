package job

#CareerPage: {
	company: string
	link:    string
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
