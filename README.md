# Red Eclipse Python masterserver

![](https://api.travis-ci.org/TheAssassin/python-masterserver.svg?branch=master)

Basic implementation of a Red Eclipse master server in Python. Can act as a proxy for other master servers by fetching their entries and rehosting them.

Lacks support for advanced features like authentication (both client and server) as of yet. Might, in the future, forward auth requests to other masterservers for entries it rehosts.
