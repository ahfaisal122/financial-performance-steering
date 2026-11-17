-- FR-1.15: the focus company, the peer and the German market side by side, per year
-- and line group. Gaps are in percentage points.
-- The market is available at total level only (EIOPA); line group rows show
-- market_status 'no market data'.
CREATE OR REPLACE VIEW analysis_peer_market AS
SELECT
    peer.year,
    peer.line_group,
    peer.is_total,
    peer.focus_insurer,
    peer.focus_loss_ratio,
    peer.peer_insurer,
    peer.peer_loss_ratio,
    COALESCE(focus_market.market, peer_market.market) AS market,
    COALESCE(focus_market.market_loss_ratio, peer_market.market_loss_ratio)
        AS market_loss_ratio,
    peer.peer_gap_pts,
    focus_market.market_gap_pts AS focus_market_gap_pts,
    peer_market.market_gap_pts AS peer_market_gap_pts,
    peer.peer_status,
    COALESCE(focus_market.market_status, 'no market data') AS market_status
FROM kpi_peer_gap AS peer
LEFT JOIN kpi_market_gap AS focus_market
    ON peer.focus_insurer = focus_market.insurer
    AND peer.year = focus_market.year
    AND peer.line_group = focus_market.line_group
LEFT JOIN kpi_market_gap AS peer_market
    ON peer.peer_insurer = peer_market.insurer
    AND peer.year = peer_market.year
    AND peer.line_group = peer_market.line_group;
