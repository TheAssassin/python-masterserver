# Red Eclipse Python masterserver

[![Build Status](https://api.travis-ci.org/TheAssassin/python-masterserver.svg?branch=master)](https://travis-ci.org/TheAssassin/python-masterserver)
[![Coverage Status](https://opencov.assassinate-you.net/projects/1/badge.svg)](https://opencov.assassinate-you.net/projects/1)

Basic implementation of a Red Eclipse master server in Python. Can act as a proxy for other master servers by fetching their entries and rehosting them.

Lacks support for advanced features like authentication (both client and server) as of yet. Might, in the future, forward auth requests to other masterservers for entries it rehosts.
