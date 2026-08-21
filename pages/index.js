import { useState, useEffect, useCallback, memo } from 'react';

const RATINGS = ['상', '중', '하'];
const fmt = (n) => (n || 0).toLocaleString();
const money = (n) => '$' + (n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const PAGE = 300;

function todayStr(offset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

export default function Home() {
  const [from, setFrom] = useState(todayStr(-30));
  const [to, setTo] = useState(todayStr(0));
  const [minGmv, setMinGmv] = useState(0);
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [visible, setVisible] = useState(PAGE);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [appKey, setAppKey] = useState('');

  useEffect(() => {
    try { setAppKey(localStorage.getItem('appKey') || ''); } catch (e) {}
  }, []);

  const headers = useCallback(() => {
    const h = { 'Content-Type': 'application/json' };
    if (appKey) h['x-app-key'] = appKey;
    return h;
  }, [appKey]);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const q = new URLSearchParams({ from, to, minGmv: String(minGmv) });
      const r = await fetch('/api/videos?' + q, { headers: headers() });
      if (r.status === 401) {
        const k = prompt('접근 키를 입력하세요');
        if (k) { localStorage.setItem('appKey', k); setAppKey(k); }
        setLoading(false); return;
      }
      const j = await r.json();
      if (j.error) throw new Error(j.error);
      setRows(j.videos || []); setCount(j.count || 0); setVisible(PAGE);
    } catch (e) { setErr(String(e.message || e)); }
    setLoading(false);
  }, [from, to, minGmv, headers]);

  // 날짜/최소GMV 변경 시 자동 재조회(400ms 디바운스)
  useEffect(() => {
    const t = setTimeout(() => { load(); }, 400);
    return () => clearTimeout(t);
  }, [from, to, minGmv, load]);

  // 저장은 useCallback으로 고정 → 행 memo가 유지되어 클릭한 행만 리렌더
  const saveReview = useCallback(async (id, patch) => {
    setRows((prev) => prev.map((v) => (v.id === id ? { ...v, ...patch, _saving: true } : v)));
    try {
      const r = await fetch('/api/review', { method: 'POST', headers: headers(), body: JSON.stringify({ id, ...patch }) });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || 'save fail');
      setRows((prev) => prev.map((v) => (v.id === id ? { ...v, _saving: false, _saved: true } : v)));
      setTimeout(() => setRows((prev) => prev.map((v) => (v.id === id ? { ...v, _saved: false } : v))), 1000);
    } catch (e) {
      alert('저장 실패: ' + (e.message || e));
      setRows((prev) => prev.map((v) => (v.id === id ? { ...v, _saving: false } : v)));
    }
  }, [headers]);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 20, maxWidth: 1400, margin: '0 auto', color: '#111' }}>
      <h2 style={{ margin: '0 0 4px' }}>d'Alba 영상 성과 · 크리에이터 평가</h2>
      <div style={{ color: '#666', fontSize: 13, marginBottom: 16 }}>
        pickdi video list 시트 기반 · 평가(상/중/하)·특이사항은 별도 리뷰 탭에 저장됩니다
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
        <label>게시일 <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <span>~</span>
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <label style={{ marginLeft: 8 }}>
          최소 GMV $<input type="number" value={minGmv} onChange={(e) => setMinGmv(Number(e.target.value))} style={{ width: 70 }} />
        </label>
        <button onClick={load} disabled={loading} style={btn}>{loading ? '불러오는 중…' : '새로고침'}</button>
        <span style={{ color: '#888', fontSize: 13 }}>
          {count.toLocaleString()}건 (표시 {Math.min(visible, rows.length).toLocaleString()})
        </span>
      </div>

      {err && <div style={{ color: '#c00', marginBottom: 10 }}>오류: {err}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f7', textAlign: 'left' }}>
              {['영상', '크리에이터', '핸들', '상품ID', '게시일', '조회수', 'GMV', 'GPM', '판매수량', '주문수', 'CTR', '평가', '특이사항'].map((h) => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, visible).map((v) => (
              <VideoRow key={v.id} v={v} onSave={saveReview} />
            ))}
            {!rows.length && !loading && (
              <tr><td colSpan={13} style={{ ...td, color: '#999', padding: 30, textAlign: 'center' }}>데이터 없음 — 날짜/최소GMV를 조정하세요</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {visible < rows.length && (
        <div style={{ textAlign: 'center', margin: '16px 0' }}>
          <button onClick={() => setVisible((n) => n + PAGE)} style={btn}>
            더 보기 (+{Math.min(PAGE, rows.length - visible)})
          </button>
        </div>
      )}
    </div>
  );
}

// 행 단위 memo — v 또는 onSave가 바뀔 때만 리렌더. 다른 행 클릭엔 영향 없음.
const VideoRow = memo(function VideoRow({ v, onSave }) {
  return (
    <tr style={{ borderBottom: '1px solid #eee' }}>
      <td style={{ ...td, maxWidth: 260 }}>
        <a href={v.link || `https://www.tiktok.com/@${v.handle}/video/${v.id}`} target="_blank" rel="noreferrer"
           style={{ color: '#0a58ca', textDecoration: 'none' }} title={v.title}>
          {v.title ? v.title.slice(0, 40) : '(제목없음)'}
        </a>
      </td>
      <td style={td}>{v.creator}</td>
      <td style={td}>{v.handle}</td>
      <td style={{ ...td, fontFamily: 'monospace', fontSize: 11, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.product}>{v.product}</td>
      <td style={td}>{v.postDate}</td>
      <td style={tdR}>{fmt(v.views)}</td>
      <td style={{ ...tdR, fontWeight: 600 }}>{money(v.gmv)}</td>
      <td style={tdR}>{v.gpm ? '$' + v.gpm.toFixed(2) : '-'}</td>
      <td style={tdR}>{fmt(v.units)}</td>
      <td style={tdR}>{fmt(v.orders)}</td>
      <td style={tdR}>{v.ctr}</td>
      <td style={td}>
        <div style={{ display: 'flex', gap: 3 }}>
          {RATINGS.map((rt) => (
            <button key={rt} onClick={() => onSave(v.id, { rating: v.rating === rt ? '' : rt })}
              style={{ ...pill, ...(v.rating === rt ? pillOn(rt) : {}) }}>{rt}</button>
          ))}
        </div>
      </td>
      <td style={td}>
        <NoteCell value={v.note} saving={v._saving} saved={v._saved}
          onSave={(note) => onSave(v.id, { note })} />
      </td>
    </tr>
  );
});

function NoteCell({ value, onSave, saving, saved }) {
  const [v, setV] = useState(value || '');
  useEffect(() => { setV(value || ''); }, [value]);
  const dirty = v !== (value || '');
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'flex-start' }}>
      <textarea value={v} onChange={(e) => setV(e.target.value)} rows={1}
        placeholder="특이사항…" style={{ width: 200, resize: 'vertical', fontSize: 12, padding: 4 }} />
      <button onClick={() => onSave(v)} disabled={!dirty || saving}
        style={{ ...btnSm, ...(dirty ? {} : { opacity: 0.4 }) }}>
        {saving ? '…' : saved ? '✓' : '저장'}
      </button>
    </div>
  );
}

const th = { padding: '8px 8px', borderBottom: '2px solid #ddd', whiteSpace: 'nowrap' };
const td = { padding: '6px 8px', verticalAlign: 'top' };
const tdR = { ...td, textAlign: 'right', whiteSpace: 'nowrap' };
const btn = { padding: '6px 14px', border: '1px solid #ccc', borderRadius: 6, background: '#111', color: '#fff', cursor: 'pointer' };
const btnSm = { padding: '4px 8px', border: '1px solid #ccc', borderRadius: 5, background: '#fff', cursor: 'pointer', fontSize: 12 };
const pill = { padding: '3px 9px', border: '1px solid #ccc', borderRadius: 12, background: '#fff', cursor: 'pointer', fontSize: 12 };
const pillOn = (rt) => ({
  background: rt === '상' ? '#1a7f37' : rt === '중' ? '#9a6700' : '#b62324',
  color: '#fff', borderColor: 'transparent', fontWeight: 700,
});
