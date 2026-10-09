export interface PeriodMeta {
  start: string;
  end: string;
  source: string;
}

export interface MetaPayload {
  replay_period: PeriodMeta;
  news_period: PeriodMeta;
}

export interface PortfolioWeight {
  date: string;
  ticker: string;
  base_weight: number;
  weight: number;
  score: number;
  smoothed_score: number;
  turnover: number;
}

export interface NavPoint {
  date: string;
  strategy_gross: number;
  strategy_5bps: number;
  strategy_10bps: number;
  equal_weight_5bps: number;
  equal_weight_buy_hold: number;
  spy: number;
  strat_ret_5bps: number;
  ew_ret_5bps: number;
  spy_ret: number;
  turnover: number;
}

export interface DrivingSignal {
  ticker?: string;
  rank: number;
  text_id: string;
  headline: string;
  source: string;
  event_type: string;
  sentiment_score: number;
  impact_score: number;
  event_confidence: number;
  attribution_weight: number;
  adj_sentiment: number;
  weight_w: number;
  sum_weights_for_ticker?: number;
  weight_share?: number;
  contribution: number;
  filtered_by_deadband: boolean;
}

export type ActionType = 'INCREASE' | 'REDUCE' | 'HOLD';

export interface PositionSnapshot {
  ticker: string;
  base_weight: number;
  prev_weight: number;
  weight: number;
  target_weight: number;
  weight_change_bps: number;
  action: ActionType;
  score: number;
  smoothed_score: number;
  raw_score: number;
  bounds_constrained: boolean;
  top_driving_signals: DrivingSignal[];
}

export interface PortfolioSnapshot {
  date: string;
  turnover: number;
  turnover_constrained: boolean;
  bounds_constrained: boolean;
  hold_threshold_bps: number;
  positions: PositionSnapshot[];
  meta: MetaPayload;
}

export interface SignalImpactResponse {
  text_id: string;
  ticker: string;
  headline: string;
  source: string;
  event_type: string;
  ts: string;
  sentiment_score: number;
  impact_score: number;
  event_confidence: number;
  sentiment_confidence?: number | null;
  attribution_weight: number;
  deadband_threshold: number;
  filtered_by_deadband: boolean;
  neg_multiplier: number;
  adj_sentiment: number;
  weight_w: number;
  sum_weights_for_ticker?: number;
  weight_share?: number;
  explanation: string;
  driving_signal_details?: {
    rebalance_date: string;
    rank: number;
    contribution: number;
    sum_weights_for_ticker?: number;
    weight_share?: number;
  } | null;
  meta: MetaPayload;
}

export interface RiskSignal {
  text_id: string;
  ticker: string;
  headline: string;
  source: string;
  event_type: string;
  ts: string;
  sentiment_score: number;
  impact_score: number;
  event_confidence: number;
  attribution_weight: number;
  is_broadcast?: boolean;
}

export interface MetaMetricsResponse {
  validation: any;
  sentiment_eval: any;
  sentiment_hand_eval: any;
  event_eval: any;
  module_a: any;
  meta: MetaPayload;
}

export interface HighImpactDay {
  date: string;
  impact_score: number;
  ticker: string;
  headline: string;
  event_type: string;
  sentiment_score: number;
  contribution: number;
  filtered_by_deadband: boolean;
}
