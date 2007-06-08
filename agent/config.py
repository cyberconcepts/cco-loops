#
#  Copyright (c) 2007 Helmut Merz helmutm@cy55.de
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""
Management of agent configuration.

$Id$
"""

from zope.interface import implements
from loops.agent.interfaces import IConfigurator


class Configurator(object):

    implements(IConfigurator)

    def loadConfiguration(self):
        pass

    def addConfigOption(self, key, value):
        setattr(self, key, value)

    def getConfigOption(self, key, value):
        return getattr(self, key, None)


conf = Configurator()

# this is just for convenience during the development phase,
# thus we can retrieve the port easily via ``conf.ui.web.port``
conf.addConfigOption('ui', Configurator())
conf.ui.addConfigOption('web', Configurator())
conf.ui.web.addConfigOption('port', 10095)

