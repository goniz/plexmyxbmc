#!/usr/bin/python2


def dict2xml(d, root_node=None):
    wrap = False if root_node is None or isinstance(d, list) else True
    root = 'objects' if root_node is None else root_node
    root_singular = root[:-1] if 's' == root[-1] and root_node is None else root
    xml = ''
    children = list()

    if isinstance(d, dict):
        for key, value in dict.items(d):
            key = key.rstrip('_')
            if isinstance(value, dict):
                children.append(dict2xml(value, key))
            elif isinstance(value, list):
                children.append(dict2xml(value, key))
            else:
                xml = xml + ' ' + key + '="' + str(value) + '"'
    else:
        for value in d:
            children.append(dict2xml(value, root_singular))

    end_tag = '>' if 0 < len(children) else '/>'

    if wrap or isinstance(d, dict):
        xml = '<' + root + xml + end_tag

    if 0 < len(children):
        for child in children:
            xml = xml + child

        if wrap or isinstance(d, dict):
            xml = xml + '</' + root + '>'

    return xml


def dict2xml_withheader(d, root_node=None):
    return '<?xml version="1.0" encoding="utf-8"?>' + dict2xml(d, root_node)