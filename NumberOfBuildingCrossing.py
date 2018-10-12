# -------------------------------------------------------------
# Name:             NumberOfBuildingCrossing.py
# Purpose:          Calculates the number of buildings between all the buildings pairs
# Author:           Elena Grigoreva, e.v.grigoryeva@gmail.com (Technical University of Munich)
# About author:     https://egrigoreva.github.io/
# Created:          12/10/2018
# Copyright:        (c) Chair of Communication Networks, Department of Electrical and Computer Engineering,
#                   Technical University of Munich
# ArcGIS Version:   10.3.1
# Python Version:   2.7
# -------------------------------------------------------------

import arcpy
import os
import pickle as pkl

arcpy.env.overwriteOutput = True


def check_exists(name):
    """
    This function check existence of the feature class, which name is specified, and deletes it, if it exists. Some 
    arcpy functions even with the activated overwrite output return errors if the feature class already exists

    :param name: check if this file already exists
    :return: 
    """
    if arcpy.Exists(name):
        arcpy.Delete_management(name)
    return


def check_object_id(layer_in):
    """
    This function checks how is the id field named in the fc
    
    :param layer_in:    the layer, where we are not sure how the field is named 
    :return: the name  of the field
    """

    # Get fields of points
    field_objects = arcpy.ListFields(layer_in)
    fields = [field.name for field in field_objects if field.type != 'Geometry']

    # Get the nodes ids
    if "OID" in fields:
        points_id = 'OID'

    elif "OBJECTID" in fields:
        points_id = 'OBJECTID'

    elif "ObjectID" in fields:
        points_id = "ObjectID"

    return points_id


def create_line(points_layer):
    """
    This function returns a line between two points.
    
    :param points_layer: feature layer, points
    :return: 
    """

    point = arcpy.Point()

    spatial_ref = arcpy.Describe(points_layer).spatialReference

    # Create an array of points
    array_tmp = arcpy.Array()
    with arcpy.da.SearchCursor(points_layer, ['SHAPE@X', 'SHAPE@Y']) as cursor:
        for row in cursor:
            # list_tmp.append(arcpy.Point(row[0], row[1]))
            point.X = row[0]
            point.Y = row[1]
            array_tmp.append(point)

            line = arcpy.Polyline(array_tmp, spatial_ref)

    line_out = os.path.join('in_memory', 'line')
    check_exists(line_out)

    arcpy.CopyFeatures_management(line, line_out)

    return line_out


def main(buildings_not_filtered, fc_out, text_file_path):
    """
    
    :param buildings_not_filtered: the buildings polygon feature class, ply
    :param fc_out: the feature class to store results
    :param text_file_path: the path to save the .pkl Python dictionaries
    :return: 
    """

    # Filter the buildings from the OSM
    filtering_layer = os.path.join('in_memory', 'filtering_layer')
    check_exists(filtering_layer)
    arcpy.MakeFeatureLayer_management(buildings_not_filtered, filtering_layer)

    clause_filtering = 'building = \'yes\''
    arcpy.SelectLayerByAttribute_management(filtering_layer, 'NEW_SELECTION', clause_filtering)

    name = arcpy.Describe(buildings_not_filtered).name
    buildings = os.path.join(fc_out, name + '_buildings_only')
    check_exists(buildings)

    arcpy.CopyFeatures_management(filtering_layer, buildings)

    arcpy.AddMessage('The buildings have been filtered from the initial polygon feature class. There are in total {0} '
                     'buildings. As the algorithm is not optimized for performance, this might take a '
                     'while.'.format(arcpy.GetCount_management(buildings).getOutput(0)))

    # Get the centroids
    centroids = os.path.join(fc_out, name + '_centroids')
    check_exists(centroids)
    arcpy.FeatureToPoint_management(buildings, centroids, 'CENTROID')

    arcpy.AddMessage('Centroinds of the buildings was calculated.')

    n_centroids = int(arcpy.GetCount_management(centroids).getOutput(0))

    # Make an iteration layer for the centroids
    layer_centroids = os.path.join('in_memory', 'layer_centroids')
    check_exists(layer_centroids)
    arcpy.MakeFeatureLayer_management(centroids, layer_centroids)

    # Make the layer of the building polygons
    layer_polygons = os.path.join('in_memory', 'layer_polygons')
    check_exists(layer_polygons)
    arcpy.MakeFeatureLayer_management(buildings, layer_polygons)

    dict_out = {}

    centroids_id_field = check_object_id(centroids)
    buildings_id_field = check_object_id(buildings)

    arcpy.AddMessage('Start of the analysis.')

    # Iterate through all the nodes
    for i in range(1, n_centroids+1):
        dict_out[i] = []
        arcpy.AddMessage('Calculating how many buildings are between the building {0} and the rest'.format(i))
        for j in range(1, n_centroids+1):
            clause_centroids = '{0} = {1} Or {0} = {2}'.format(centroids_id_field, i, j)
            arcpy.SelectLayerByAttribute_management(layer_centroids, 'NEW_SELECTION', clause_centroids)

            # Between the centroids create a line
            line = create_line(layer_centroids)

            line_layer = os.path.join('in_memory', 'line_layer')
            check_exists(line_layer)
            arcpy.MakeFeatureLayer_management(line, line_layer)

            # From spatial intersection get the number of intersecting building polygons
            # The number of intersecting points -2 (initial points)
            arcpy.SelectLayerByLocation_management(layer_polygons, overlap_type='INTERSECT', select_features=line_layer,
                                                   selection_type='NEW_SELECTION')

            n_crossed_building = 0

            with arcpy.da.SearchCursor(layer_polygons, buildings_id_field) as cursor:
                for row in cursor:
                    n_crossed_building += 1

            dict_out[i].append(n_crossed_building)
            arcpy.AddMessage(dict_out[i])

    print(dict_out)

    # Add the geographical coordinates
    arcpy.AddMessage('Saving the geographical coordinates to a Python dictionary')
    arcpy.AddXY_management(centroids)

    geo_coord = {}

    with arcpy.da.SearchCursor(centroids, [centroids_id_field, 'POINT_X', 'POINT_Y']) as cursor:
        for row in cursor:
            geo_coord[row[0]] = (row[1], row[2])

    print(geo_coord)

    # Save the dictionaries
    # Coordinates
    f_geo_path = os.path.join(text_file_path, 'BuildingCentroids.pkl')

    with open(f_geo_path, 'wb') as f_geo:
        pkl.dump(geo_coord, f_geo)

    # Number of buiding intersections
    f_int_path = os.path.join(text_file_path, 'BuildingsIntersections.pkl')

    with open(f_int_path, 'wb') as f_int:
        pkl.dump(dict_out, f_int)

    # # Test reading out
    # with open(f_geo_path, 'rb') as f_geo:
    #     print(pkl.load(f_geo))
    #
    # with open(f_int_path, 'rb') as f_int:
    #     print(pkl.load(f_int))

    arcpy.AddMessage('The results have been saved as BuildingCentroids.pkl and BuildingsIntersections.pkl in the '
                     'specified folder {0}'.format(text_file_path))

    return


if __name__ == '__main__':
    input = False

    if input:
        buildings_in = r'D:\GISworkspace\5_OtherProjects\2_CarmenPropagation\UK_Eden.gdb\Results\Eden_osm_ply_1'
        fc_out_in = r'D:\GISworkspace\5_OtherProjects\2_CarmenPropagation\UK_Eden.gdb\Results'
        text_file_path_in = r'D:\GISworkspace\5_OtherProjects\2_CarmenPropagation'

    else:
        buildings_in = arcpy.GetParameterAsText(0)
        fc_out_in = arcpy.GetParameterAsText(1)
        text_file_path_in = arcpy.GetParameterAsText(2)

    main(buildings_in, fc_out_in, text_file_path_in)