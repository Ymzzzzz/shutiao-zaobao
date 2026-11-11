#!/usr/bin/env python3
"""content-v2 字段校验（spec/content-v2.md §2）。用法：
  python3 check_v2.py <digest.json> [--img-root <data 目录>] [--strict-coverage]
img-root 给出时检查图片文件存在且 ≤100KB。退出码 1 = 有错误。"""
import json,re,sys,os
CJK=re.compile(r'[\u3400-\u9fff]'); LAT=re.compile(r'[A-Za-z]')
def n_chars(t): return len(re.sub(r'\*\*|\s','',t))
def zh_ratio(t):
    c=len(CJK.findall(t)); l=len(LAT.findall(t)); return c/max(1,c+l), c
NEW=["title_zh","lead_zh","body_zh","image_url","image_source","image_origin_url"]
KINDS={"facts","claims","analysis"}
def check_item(n,img_root=None):
    E=[];W=[];i=n.get('id','?')
    for k in NEW:
        if k not in n: E.append(f'{i}: 缺字段 {k}')
    if E: return E,W
    names={s['name'] for s in n.get('sources',[])}
    t=n['title_zh']; l=n['lead_zh']; b=n['body_zh']
    if not isinstance(t,str) or not isinstance(l,str) or not isinstance(b,list): E.append(f'{i}: 类型错误'); return E,W
    if t:
        r,c=zh_ratio(t)
        if not 6<=n_chars(t)<=40: E.append(f'{i}: title_zh 长度 {n_chars(t)}，应 6–40')
        if c<6 or r<0.3: E.append(f'{i}: title_zh 不是中文（汉字 {c} 个，占比 {r:.2f}）')
        if t.strip()==n.get('original_title','').strip() and c==0: E.append(f'{i}: title_zh 直接用了英文原标题')
    if l:
        r,c=zh_ratio(l)
        if not 30<=n_chars(l)<=90: E.append(f'{i}: lead_zh 长度 {n_chars(l)}，应 30–90')
        if r<0.5: E.append(f'{i}: lead_zh 中文占比 {r:.2f} < 0.5')
        if '\n' in l: E.append(f'{i}: lead_zh 不能换行')
    if (l or b) and not t: E.append(f'{i}: 有 lead_zh/body_zh 却没有 title_zh')
    if b:
        if not l: E.append(f'{i}: 有 body_zh 却没有 lead_zh')
        if not 1<=len(b)<=4: E.append(f'{i}: body_zh 小节数 {len(b)}，应 1–4')
        if b and b[0].get('kind')!='facts': E.append(f'{i}: body_zh 第一个小节必须是 facts')
        allp=[]
        for j,s in enumerate(b):
            if s.get('kind') not in KINDS: E.append(f'{i}: body_zh[{j}].kind 非法')
            h=s.get('heading','')
            if not 2<=n_chars(h)<=12: E.append(f'{i}: body_zh[{j}].heading 长度应 2–12')
            ps=s.get('paras') or []
            if not ps or not all(isinstance(p,str) and p.strip() for p in ps): E.append(f'{i}: body_zh[{j}].paras 为空')
            if sum(p.count('**')//2 for p in ps)>10: E.append(f'{i}: body_zh[{j}] 高亮超过 10 处')
            for p in ps:
                if not 40<=n_chars(p)<=250: E.append(f'{i}: body_zh[{j}] 段落 {n_chars(p)} 字，应 40–250')
                if p.count('**')%2: E.append(f'{i}: body_zh[{j}] 的 ** 没有成对')
                if re.search(r'https?://',p): E.append(f'{i}: body_zh 正文里不放链接')
            src=s.get('sources') or []
            if not src or not set(src)<=names: E.append(f'{i}: body_zh[{j}].sources 必须非空且都在 sources[].name 里')
            if s.get('kind')=='analysis' and not n.get('analysis'): W.append(f'{i}: 有 analysis 小节但 analysis 数组为空')
            allp+=ps
        body=''.join(allp); r,_=zh_ratio(body); L=n_chars(body)
        if not 300<=L<=600: E.append(f'{i}: body_zh 正文 {L} 字，应 300–600')
        if r<0.5: E.append(f'{i}: body_zh 中文占比 {r:.2f} < 0.5')
    iu,iso,io_=n['image_url'],n['image_source'],n['image_origin_url']
    for k in ('image_url','image_source','image_origin_url'):
        if not isinstance(n[k],str): E.append(f'{i}: {k} 必须是字符串（无图用 ""，不用 null）')
    if isinstance(iu,str):
        if iu:
            if not re.match(r'^img/[A-Za-z0-9_\-]+\.jpg$',iu): E.append(f'{i}: image_url 格式应为 img/<名>.jpg')
            if not iso or iso not in names: E.append(f'{i}: image_source「{iso}」必须是 sources[].name 之一')
            if not re.match(r'^https://',io_ or ''): E.append(f'{i}: 有图时 image_origin_url 必须是 https 原图地址')
            if img_root:
                p=os.path.join(img_root,iu)
                if not os.path.exists(p): E.append(f'{i}: 图片文件不存在 {p}')
                elif os.path.getsize(p)>100*1024: E.append(f'{i}: 图片 {os.path.getsize(p)//1024}KB > 100KB')
        elif iso or io_: E.append(f'{i}: image_url 为空时 image_source/image_origin_url 也必须为空')
    return E,W
def main():
    a=sys.argv[1:]; f=a[0]; root=a[a.index('--img-root')+1] if '--img-root' in a else None
    d=json.load(open(f)); E=[];W=[]
    for n in d['items']:
        e,w=check_item(n,root); E+=e; W+=w
    it=d['items']; tot=len(it) or 1
    must=[n for n in it if n['id'] in d.get('top_items',[]) or n.get('importance',1)>=2]
    cov=lambda k,xs:sum(1 for n in xs if n.get(k))
    print(f"条目 {len(it)}：title_zh {cov('title_zh',it)}/{len(it)}，lead_zh {cov('lead_zh',it)}/{len(it)}，body_zh {cov('body_zh',it)}/{len(it)}，有图 {cov('image_url',it)}/{len(it)}")
    print(f"必须完整的（top_items + importance≥2）{len(must)} 条：body_zh 完整 {cov('body_zh',must)}/{len(must)}")
    if '--strict-coverage' in a:
        for n in must:
            if not (n['title_zh'] and n['lead_zh'] and n['body_zh']): E.append(f"{n['id']}: top/importance≥2 条目缺中文标题/导语/正文")
        if cov('title_zh',it)<len(it): E.append('title_zh 覆盖率 < 100%')
        if cov('lead_zh',it)<len(it): E.append('lead_zh 覆盖率 < 100%')
    for w in W: print('警告',w)
    for e in E: print('错误',e)
    print('通过' if not E else f'不通过：{len(E)} 个错误'); sys.exit(1 if E else 0)
if __name__=='__main__': main()
