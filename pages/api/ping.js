// 의존성 없는 헬스체크. /api/ping 이 JSON을 주면 함수 배포는 정상.
module.exports = function handler(req, res) {
  res.status(200).json({ ok: true, ts: Date.now(), node: process.version });
};
