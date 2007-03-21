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
View classes for versioning.

$Id$
"""

from zope import interface, component
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.app.security.interfaces import IUnauthenticatedPrincipal
from zope.cachedescriptors.property import Lazy

from loops.browser.common import BaseView
from loops.versioning.interfaces import IVersionable
from loops.versioning.util import getVersion


class ListVersions(BaseView):

    template = ViewPageTemplateFile('version_macros.pt')

    @Lazy
    def macro(self):
        return self.template.macros['versions']

    def __init__(self, context, request):
        super(ListVersions, self).__init__(context, request)
        cont = self.controller
        if (cont is not None and not IUnauthenticatedPrincipal.providedBy(
                                                    self.request.principal)):
            cont.macros.register('portlet_right', 'versions', title='Versions',
                         subMacro=self.template.macros['portlet_versions'],
                         info=self)

    def versions(self):
        versionable = IVersionable(self.context)
        versions = versionable.versions
        for v in sorted(versions):
            yield BaseView(versions[v], self.request)

