import twisted
from twisted.internet import default

twisted._checkRequirements()

default._getInstallFunction('mac')
