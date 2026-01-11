import json
import os
import logging
import types
import inspect
from  config import PROPS_FILE

logger = logging.getLogger(__name__)

def json_file_to_path_dict(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = {}

    def walk(node, prefix=""):
        if isinstance(node, dict):
            for k, v in node.items():
                path = f"{prefix}.{k}" if prefix else k
                walk(v, path)
        else:
            result[prefix] = node

    walk(data)
    return result

def path_dict_to_json(path_dict):
    result = {}

    for path, value in path_dict.items():
        if not callable(value):
            parts = path.split(".")
            node = result

            for p in parts[:-1]:
                node = node.setdefault(p, {})

            node[parts[-1]] = value

    return result

class PropertyManager:
    def __init__(self, filename=PROPS_FILE):
        logger.info(f"PropertyManager {filename}")
        self.props = {}
        self.filename = filename
        self.load()
        #print(f"PROPS { self.props}")

    def resolve(self,key,value):
        #if callable(value):
     
        if callable(value):
            return value()
        else:
            return value
    
    def get(self, path, def_value=None):
        
        if path in self.props:
            return self.resolve(path,self.props[path])
        else:
            list=[]
            for k,v in self.props.items():
                if k.startswith(path):
                    list.append({k:self.resolve(k,v)})
            if len(list)>0:
                return list
        if def_value is not None:
            self.props[path] = def_value
            return def_value
        return None
    
    def add_computed(self,name,handler):
        self.props[name] = handler

    def get_computed_list(self):
        list = []
        for path, value in self.props.items():
            if  callable(value):
                list.append({path:value})
        return list
        
    def get_computed_snap(self):
        snap=[]
        for item in self.get_computed_list():
            for path, value in item.items():
                snap.append(path+"="+str(value()))
        return snap

    async def set(self, path, value, onChange):
        snap=self.get_computed_snap()
        #logger.info(f"COMPUTED {snap}")
        self.props[path] = value
        snap_new=self.get_computed_snap()
        
        if onChange:
            for i in range(len(snap)):
                if (snap_new[i] != snap[i]):
                    logger.info(f"CHANGED {snap[i]}")
                    await onChange(self.get_computed_list()[i])

        self.save()

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            _json = path_dict_to_json(self.props )
            json.dump(_json, f, indent=2, ensure_ascii=False)

    def load(self):
        if os.path.exists(self.filename):
            try:
                self.props = json_file_to_path_dict(self.filename)
                #print(self.props )
                #json = path_dict_to_json(self.props )
                #print(json)
            except (json.JSONDecodeError, IOError):
                self.props = {}
        else:
            logger.error(f"File not found {self.filename}")

if __name__ =="__main__":
    p = PropertyManager("config/properties.json")
    def comp():
        return 33
    p.add_computed("trade.a", comp)

    #p.save()
    print(p.get("trade"))
    print(p.get("trade.day_risk"))
 