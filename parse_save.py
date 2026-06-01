"""
GVAS Parser for Deep Rock Galactic save files.

Size field semantics (verified by binary analysis):
  StructProperty:  size = bytes of sub-props (after struct_type_str + 17 GUID/tag bytes)
                   → data_end = after_struct_type + 17 + size
  ArrayProperty:   size = len(payload) - len(itype_str_bytes) - 1(tag byte)
                   → true_end = payload_start + len(itype_bytes) + 1 + size
  Scalar types:    size = data bytes only (tag byte excluded)
                   → reads: tag(1) + size bytes
  BoolProperty:    size=0, reads tag(1) + padding(1)
  Unknown types:   treated as scalars → skip tag(1) + size bytes
"""
import struct, json, sys

# Garde-fous anti-DoS (#1, V9). Un .sav forgé pourrait imbriquer des structs à
# l'infini (récursion → stack overflow) ou annoncer un `count` de tableau énorme
# (boucle longue). On borne les deux. Les vraies saves DRG restent loin de ces seuils.
MAX_DEPTH = 100  # profondeur d'imbrication des propriétés

def rs(data, o):
    l, = struct.unpack_from('<i', data, o); o += 4
    if l == 0: return "", o
    if l < 0:
        l2=-l; s=data[o:o+l2*2].decode('utf-16-le','replace').rstrip('\x00')
        return s, o+l2*2
    if l > 500000: raise ValueError(f"Bad str len {l} @ {o-4}")
    return data[o:o+l-1].decode('utf-8','replace'), o+l

class GVASParser:
    def __init__(self, data): self.d = data
    def i32(self,o): v,=struct.unpack_from('<i',self.d,o); return v,o+4
    def u32(self,o): v,=struct.unpack_from('<I',self.d,o); return v,o+4
    def i64(self,o): v,=struct.unpack_from('<q',self.d,o); return v,o+8
    def f32(self,o): v,=struct.unpack_from('<f',self.d,o); return round(v,4),o+4
    def u8(self,o):  v,=struct.unpack_from('<B',self.d,o); return v,o+1
    def str(self,o): return rs(self.d,o)
    def guid(self,o): return self.d[o:o+16].hex(),o+16

    def parse_props(self, o, end=None, depth=0):
        if end is None: end = len(self.d)
        if depth > MAX_DEPTH:
            raise ValueError(f"Nesting too deep (>{MAX_DEPTH}) @ {o}")
        obj = {}
        while o < end - 4:
            try: name, o = self.str(o)
            except: break
            if name in ("None", ""): break
            try:
                tname, o = self.str(o)
                size,    o = self.i64(o)
            except: break
            val, o = self.parse_val(o, tname, size, depth)
            obj[name] = val
        return obj, o

    def parse_val(self, o, tname, size, depth=0):
        # --- Scalar types: tag(1) + size bytes ---
        if tname == "BoolProperty":
            v, o = self.u8(o); return bool(v), o+1   # tag=value, +1 padding

        if tname == "IntProperty":    o+=1; return self.i32(o)
        if tname == "UInt32Property": o+=1; return self.u32(o)
        if tname == "Int64Property":  o+=1; return self.i64(o)
        if tname == "FloatProperty":  o+=1; return self.f32(o)

        if tname in ("StrProperty","NameProperty","TextProperty"):
            o+=1; return self.str(o)
        if tname == "ObjectProperty": o+=1; return self.str(o)

        if tname == "EnumProperty":
            _, o = self.str(o); o+=1; return self.str(o)

        # --- Container types ---
        if tname == "StructProperty":
            stype, o = self.str(o)
            o += 17                        # GUID(16) + tag(1)
            data_end = o + size            # size = sub-prop bytes only
            if stype == "Guid":
                v, o = self.guid(o)
            elif stype in ("DateTime","Timespan"):
                v, o = self.i64(o)
            else:
                v, o = self.parse_props(o, data_end, depth + 1)
                v["_type"] = stype
            return v, data_end

        if tname == "ArrayProperty":
            payload_start = o
            itype_str, o = self.str(o)
            itype_bytes = 4 + len(itype_str) + 1
            true_end = payload_start + itype_bytes + 1 + size  # +1 for tag

            o += 1; count, o = self.i32(o)
            arr = []

            # `count` est lu DIRECTEMENT du fichier : un .sav forgé pourrait y mettre
            # une valeur énorme → boucle interminable. Chaque item pèse au moins 1
            # octet, donc count ne peut pas dépasser le nombre d'octets restants.
            if count < 0 or count > len(self.d):
                raise ValueError(f"Bad array count {count} @ {o-4}")

            if itype_str == "StructProperty":
                _, o  = self.str(o)
                _, o  = self.str(o)
                _, o  = self.i64(o)        # inner_size (total items)
                st, o = self.str(o)
                o    += 17
                for _ in range(count):
                    if st == "Guid":
                        item, o = self.guid(o)
                    else:
                        item, o = self.parse_props(o, true_end, depth + 1)
                        item["_type"] = st
                    arr.append(item)

            elif itype_str == "IntProperty":
                for _ in range(count): v,o=self.i32(o); arr.append(v)
            elif itype_str == "UInt32Property":
                for _ in range(count): v,o=self.u32(o); arr.append(v)
            elif itype_str in ("StrProperty","NameProperty","EnumProperty",
                               "ObjectProperty","SoftObjectProperty"):
                for _ in range(count): v,o=self.str(o); arr.append(v)
            elif itype_str == "BoolProperty":
                for _ in range(count): v,o=self.u8(o); arr.append(bool(v))
            else:
                return f"[Array<{itype_str}> x{count} unparsed]", true_end

            return arr, true_end

        # --- Unknown/skipped: treat like scalar (tag + size bytes) ---
        return f"[{tname} size={size} skipped]", o + 1 + size


def parse_gvas(filepath):
    with open(filepath,"rb") as f: data=f.read()
    o=4; o+=4+4+2+2+2+4
    sl,=struct.unpack_from('<i',data,o); o+=4+sl
    o+=4
    cnt,=struct.unpack_from('<I',data,o); o+=4
    o+=cnt*20
    sl2,=struct.unpack_from('<i',data,o); o+=4+sl2
    p=GVASParser(data)
    result,_=p.parse_props(o,len(data))
    return result

if __name__=="__main__":
    path=sys.argv[1] if len(sys.argv)>1 else \
        "/sessions/dazzling-tender-bohr/mnt/drg_dashboard/Saved/SaveGames/76561197983653885_Player.sav"
    result=parse_gvas(path)
    out="/sessions/dazzling-tender-bohr/mnt/outputs/player_save.json"
    with open(out,"w") as f: json.dump(result,f,indent=2,default=str)
    print(f"✅ {len(result)} top-level props")
    for k,v in result.items():
        if isinstance(v,dict):   print(f"  {k}: dict({len(v)} clés)")
        elif isinstance(v,list): print(f"  {k}: list({len(v)} items)")
        else:                    print(f"  {k}: {str(v)[:80]}")
