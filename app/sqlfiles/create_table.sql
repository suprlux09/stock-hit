CREATE TABLE IF NOT EXISTS request_list(
	key INTEGER, 
	symbol VARCHAR(30), 
	user_id INTEGER, 
	target FLOAT, 
	recent FLOAT,
	is_lower BOOLEAN
)
