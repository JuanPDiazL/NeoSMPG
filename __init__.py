# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QSMPG
                                 A QGIS plugin
 New implementation of SMPG
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-09-23
        copyright            : (C) 2023 by Juan Pablo Diaz Lombana
        email                : email.not@defined.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QSMPG class from file QSMPG.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qsmpg import QSMPG
    return QSMPG(iface)
