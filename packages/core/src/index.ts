export type CaptureEvent = {
  id: string;
  source: {
    kind: string;
    uri?: string;
    accountId?: string;
  };
  occurredAt: string;
  payload: CapturePayload;
  metadata?: Record<string, unknown>;
  provenance: Provenance;
  idempotencyKey: string;
};

export type CapturePayload =
  | { type: "text"; text: string; contentType?: string }
  | { type: "html"; html: string; url?: string }
  | { type: "binary"; mediaType: string; bytesRef: string };

export type Provenance = {
  adapterName: string;
  adapterVersion: string;
  sourceItemId?: string;
  fetchedAt: string;
};

export type EnrichmentTask =
  | { type: "classify"; labels: string[] }
  | { type: "extract"; schema: Record<string, unknown> }
  | { type: "summarize"; maxTokens?: number };

export type EnrichmentResult = {
  taskType: EnrichmentTask["type"];
  output: unknown;
  model: {
    provider: string;
    name: string;
    version?: string;
  };
  usage?: {
    inputTokens?: number;
    outputTokens?: number;
    costMicros?: number;
  };
};

export interface AdapterPort {
  readonly name: string;
  readonly version: string;
  discover(context: AdapterContext): AsyncIterable<CaptureEvent>;
}

export interface AIProviderPort {
  readonly name: string;
  run(
    task: EnrichmentTask,
    event: CaptureEvent,
    context: AIProviderContext,
  ): Promise<EnrichmentResult>;
}

export interface PersistencePort {
  readonly name: string;
  saveRaw(
    event: CaptureEvent,
    context: PersistenceContext,
  ): Promise<PersistenceResult>;
  saveEnriched(
    event: CaptureEvent,
    result: EnrichmentResult,
    context: PersistenceContext,
  ): Promise<PersistenceResult>;
  commitCheckpoint(
    checkpoint: Checkpoint,
    context: PersistenceContext,
  ): Promise<void>;
}

export type AdapterContext = {
  signal: AbortSignal;
  checkpoint?: Checkpoint;
  traceId: string;
};

export type AIProviderContext = {
  signal: AbortSignal;
  traceId: string;
};

export type PersistenceContext = {
  signal: AbortSignal;
  traceId: string;
};

export type Checkpoint = {
  adapterName: string;
  cursor: string;
  committedAt: string;
};

export type PersistenceResult =
  | { status: "committed"; recordId: string }
  | { status: "duplicate"; recordId: string }
  | { status: "conflict"; reason: string };
