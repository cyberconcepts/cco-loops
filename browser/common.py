#
#  Copyright (c) 2006 Helmut Merz helmutm@cy55.de
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
Common base class for loops browser view classes.

$Id$
"""

from zope.app import zapi
from zope.app.dublincore.interfaces import ICMFDublinCore
from zope.app.form.browser.interfaces import ITerms
from zope.cachedescriptors.property import Lazy
from zope.interface import implements
from zope.security.proxy import removeSecurityProxy

from loops import util
from loops.target import getTargetTypes

class BaseView(object):

    def __init__(self, context, request):
        #self.context = context
        self.context = removeSecurityProxy(context)
        self.request = request

    @Lazy
    def modified(self):
        """ get date/time of last modification
        """
        dc = ICMFDublinCore(self.context)
        d = dc.modified or dc.created
        return d and d.strftime('%Y-%m-%d %H:%M') or ''

    @Lazy
    def loopsRoot(self):
        return self.context.getLoopsRoot()
    
    @Lazy
    def url(self):
        return zapi.absoluteURL(self.context, self.request)

    @Lazy
    def token(self):
        return self.loopsRoot.getLoopsUri(self.context)

    @Lazy
    def title(self):
        return self.context.title or zapi.getName(self.context)

    @Lazy
    def value(self):
        return self.context

    @Lazy
    def typeTitle(self):
        voc = util.KeywordVocabulary(getTargetTypes())
        token = '.'.join((self.context.__module__,
                          self.context.__class__.__name__))
        term = voc.getTermByToken(token)
        return term.title

    @Lazy
    def typeUrl(self):
        return None

    def viewIterator(self, objs):
        request = self.request
        for o in objs:
            yield BaseView(o, request)


class LoopsTerms(object):
    """ Provide the ITerms interface, e.g. for usage in selection
        lists.
    """

    implements(ITerms)

    def __init__(self, source, request):
        # the source parameter is a view or adapter of a real context object:
        self.source = source
        self.context = source.context
        self.request = request

    @Lazy
    def loopsRoot(self):
        return self.context.getLoopsRoot()
    
    def getTerm(self, value):
        return BaseView(value, self.request)

    def getValue(self, token):
        return self.loopsRoot.loopsTraverse(token)


