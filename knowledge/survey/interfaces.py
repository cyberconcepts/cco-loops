#
#  Copyright (c) 2013 Helmut Merz helmutm@cy55.de
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
Interfaces for surveys used in knowledge management.
"""

from zope.interface import Interface, Attribute
from zope import interface, component, schema

from cybertools.knowledge.survey import interfaces
from loops.interfaces import IConceptSchema


class IQuestionnaire(IConceptSchema, interfaces.IQuestionnaire):
    """ A collection of questions for setting up a survey.
    """

    defaultOptions = Attribute('A sequence of answer options to select from. '
                'Default value used for questions that do not '
                'explicitly provide the values attribute.')


class IQuestion(IConceptSchema, interfaces.IQuestion):
    """ A single question within a questionnaire.
    """

    text = Attribute('The question asked.')
    options = Attribute('A sequence of answer options to select from.')


class IResultElement(IConceptSchema, interfaces.IResultElement):
    """ Some text (e.g. a recommendation) or some other kind of information
        that may be deduced from the res)ponses to a questionnaire.
    """

    text = Attribute('A text representing this result element.')


class IResponse(interfaces.IResponse):
    """ A set of response values given to the questions of a questionnaire
        by a single person or party.
    """
    
