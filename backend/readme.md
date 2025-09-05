Method	Endpoint	            Body Format (JSON)
-----------------------------------------------------------------
POST	/create/<table>	        { "column": "value", ... }
GET	    /read/<table>	        –
PUT	    /update/<table>/<id>	{ "column": "new_value", ... }
DELETE	/delete/<table>/<id>	–
GET	    /show_all	            –