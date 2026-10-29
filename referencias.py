"""Referencias elegidas de material: metadatos, sin leer PDFs ni consultar el campus."""
from rutas import Path
from urllib.parse import urlsplit,parse_qs,unquote
import hashlib
import re
import copy

from validar_cuaderno import web_reference


def stable(subject,value):
    return 'reference-'+hashlib.sha256((subject+':'+value).encode('utf-8')).hexdigest()[:32]


def collect_references(config,subject):
    references={};paths={};warnings=[]
    for source in [*subject.get('materials',[]),*subject.get('sources',[])]:
        if isinstance(source,dict) and 'webTopicId' in source:continue
        if isinstance(source,str):
            location=source.strip();title=location;detail=''
        elif isinstance(source,dict):
            location=source.get('path') or source.get('url') or ''
            title=source.get('title') or re.split(r'[\\/]',location)[-1];detail=source.get('detail','')
        else:
            warnings.append('Una referencia sin formato reconocible no se ha trasladado.');continue
        if not isinstance(location,str) or not isinstance(title,str):raise ValueError('Revisa el título y la ubicación de un material.')
        if location.startswith('obsidian:'):
            selected=parse_qs(urlsplit(location).query).get('file',[''])[0]
            if selected.replace('\\','/')==subject.get('note','').replace('\\','/'):continue
            location=unquote(selected)
        kind='web' if re.match(r'^https?://',location,re.I) else 'local-file' if re.search(r'\.[A-Za-z0-9]{1,8}(?:#[^/]*)?$',location) else 'description'
        # Las listas antiguas admiten texto libre como «DATOS: uno.csv, dos.csv».
        # Su extension final no lo convierte en una ruta; conserva la descripcion.
        if isinstance(source,str) and re.match(r'^[^:/\\]+:\s+\S',location):
            kind='description'
        private_path=None;original=location
        if kind=='local-file':
            private_path=(config['vaults']['degree']/location).resolve()
            if private_path==(config['vaults']['degree']/subject['note']).resolve():continue
            # Las rutas privadas solo se utilizan en el programa que ya las tenía elegidas.
            if re.match(r'^[A-Za-z]:',location) or location.startswith(('/','\\')) or '..' in location.replace('\\','/').split('/'):
                location=re.split(r'[\\/]',location)[-1]
            if not title or title==original:title=re.split(r'[\\/]',location)[-1]
        if not title:continue
        value=web_reference({'id':source.get('referenceId') or stable(subject['id'],kind+':'+original) if isinstance(source,dict) else stable(subject['id'],kind+':'+original),
                             'title':title,'kind':kind,'location':location,'detail':detail,
                             'link':source.get('url','') if isinstance(source,dict) and re.match(r'^https?://',str(source.get('url','')),re.I) and kind!='web' else '',
                             'archived':isinstance(source,dict) and source.get('archived') is True})
        references.setdefault(value['id'],value)
        if private_path is not None:paths[value['id']]=(private_path,value['location'])
    managed=subject.get('webReferences',[])
    if not isinstance(managed,list):raise ValueError('Las referencias del cuaderno necesitan una lista.')
    seen=set()
    for row in managed:
        value=web_reference(row)
        if value['id'] in seen:raise ValueError('Hay referencias repetidas en la asignatura.')
        seen.add(value['id']);references[value['id']]=value
    if len(references)>200:raise ValueError('Máximo 200 referencias de material por asignatura.')
    return list(references.values()),paths,warnings


def local_materials(config,subject):
    references,paths,warnings=collect_references(config,subject);materials=[]
    for row in references:
        if row['archived']:continue
        value={'title':row['title'],'referenceId':row['id'],'detail':row['detail'],'referenceKind':row['kind']}
        if row['link']:value['url']=row['link']
        if row['kind']=='web':value['url']=row['location']
        elif row['kind']=='local-file':
            existing=paths.get(row['id'])
            path=existing[0] if existing and existing[1]==row['location'] else (config['vaults']['degree']/row['location']).resolve()
            # Una nueva ruta relativa solo se vincula dentro de esta bóveda.
            allowed=bool(existing and existing[0]==path) or path.is_relative_to(config['vaults']['degree'])
            available=allowed and path.is_file();value['path']=str(path) if available else row['location']
            value['materialStatus']='Referencia a un archivo local; su contenido no se ha leído.' if available else 'Archivo no localizado en este equipo. Elige o aporta el enunciado antes de estudiar.'
        else:value['materialStatus']='Descripción del material; el enunciado está pendiente de aportar.'
        materials.append(value)
    return materials,warnings


def backup_references(config,subject):
    """Estabiliza identidades al reubicar las rutas privadas de una copia."""
    result=copy.deepcopy(subject)
    for key in ('materials','sources'):
        normalized=[]
        for source in subject.get(key,[]):
            selected={**subject,'materials':[source],'sources':[],'webReferences':[]}
            refs,_,_=collect_references(config,selected)
            if not refs:normalized.append(copy.deepcopy(source));continue
            ref=refs[0]
            if isinstance(source,dict):item={**source,'referenceId':ref['id']}
            else:
                item={'title':source,'referenceId':ref['id']}
                if ref['kind']=='local-file':item['path']=source
                elif ref['kind']=='web':item['url']=source
            normalized.append(item)
        if key in subject:result[key]=normalized
    return result
