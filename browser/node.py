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
View class for Node objects.

$Id$
"""

from zope.cachedescriptors.property import Lazy
from zope.app import zapi
from zope.app.container.browser.contents import JustContents
from zope.app.dublincore.interfaces import ICMFDublinCore
from zope.proxy import removeAllProxies
from zope.security import canAccess, canWrite
from zope.security.proxy import removeSecurityProxy

from loops.resource import MediaAsset

class NodeView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def render(self, text=None):
        if text is None:
            text = self.context.body
        if not text:
            return u''
        if text.startswith('<'):  # seems to be HTML
            return text
        source = zapi.createObject(self.context.contentType, text)
        view = zapi.getMultiAdapter((removeAllProxies(source), self.request))
        return view.render()

    @Lazy
    def modified(self):
        """ get date/time of last modification
        """
        dc = ICMFDublinCore(self.context)
        d = dc.modified or dc.created
        return d and d.strftime('%Y-%m-%d %H:%M') or ''

    @Lazy
    def target(self):
        return self.context.target

    @Lazy
    def page(self):
        page = self.context.getPage()
        return page is not None and NodeView(page, self.request) or None

    def textItems(self):
        for child in self.context.getTextItems():
            yield NodeView(child, self.request)

    @Lazy
    def menu(self):
        menu = self.context.getMenu()
        return menu is not None and NodeView(menu, self.request) or None

    def menuItems(self):
        for child in self.context.getMenuItems():
            yield NodeView(child, self.request)

    @Lazy
    def body(self):
        return self.render()

    @Lazy
    def url(self):
        return zapi.absoluteURL(self.context, self.request)

    @Lazy
    def editable(self):
        return canWrite(self.context, 'body')

    def selected(self, item):
        return item.context == self.context


class ConfigureBaseView(object):
    """ Helper view class for editing/configuring a node, providing the
        stuff needed for creating a target object.
    """

    def __init__(self, context, request):
        self.context = removeSecurityProxy(context)
        self.request = request

    def checkCreateTarget(self):
        form = self.request.form
        if 'field.createTarget' in form:
            type = self.request.form.get('field.targetType',
                                         'loops.resource.MediaAsset')
            # TODO: find class (better: factory) from type name
            uri = self.request.form.get('field.targetUri', None)
            # TODO: generate uri/__name__ if not given
            if uri:
                # TODO: find container
                self.context.getLoopsRoot()['resources']['ma07'] = MediaAsset()
                #self.context.loopsRoot['resources']['ma07'] = MediaAsset()

class ConfigureView(object):
    """ An editing view for configuring a node, optionally creating
        a target object.
    """

    def __init__(self, context, request):
        super(ConfigureView, self).__init__(context, request)
        self.delegate = ConfigureBaseView(context, request)

    def update(self):
        if self.update_status is not None:
            return self.update_status
        self.delegate.checkCreateTarget()
        return super(ConfigureView, self).update()

