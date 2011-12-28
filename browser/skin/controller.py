#-*- coding: UTF-8 -*-
#
#  Copyright (c) 2011 Helmut Merz helmutm@cy55.de
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
View controller for the FuFo skin.
"""

from cybertools.browser.blue.controller import Controller as BaseController


metaTagNames = ('keywords', 'description', 'google-site-verification')


class Controller(BaseController):

    def __init__(self, context, request):
        super(Controller, self).__init__(context, request)
        self.setupMetadata()

    def setupMetadata(self):
        macros = self.macros
        target = self.view.virtualTarget
        if target is not None:
            desc = target.dcDescription
            if desc:
                for line in desc.splitlines():
                    if ':' in line:
                        name, value = line.split(':')
                        if name in metaTagNames:
                            macros.register('meta', name, metaName=name,
                                            metaContent=value)
