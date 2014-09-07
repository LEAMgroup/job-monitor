leam.monitor
============
A simple polling process that checks the queue on the plone site and executes any job that is ready to run.

The polling process requests pop_queue against the plone site. If a job is queued a response will include a title, 
an ID, the repository, and the cmdline.  If repository is given then the poll.py should checkout the latest code into 
a working directory otherwise an empty working directory will be created.  In both cases the working directory name will
be the ID provided in the response.  Next the cmdline should be executed in the working directory.  Poll.py will wait 
for the processes to complete before returning polling for the next job.

*Poll.py is currently setup to be backwards compatiable with our VERY early portals.  The use of XML-RPC is 
depricated in favor of a more RESTful approach using JSON.* 

Installation
------------
Run the following command in the desired folder:

git clone https://github.com/LEAMGroup/leam.monitor

Requires
--------
[requests](http://docs.python-requests.org/en/latest/) - an HTTP library, written in Python, for human beings

