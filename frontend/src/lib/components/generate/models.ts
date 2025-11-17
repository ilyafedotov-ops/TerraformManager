export type ServiceBusPreset = {
    id: string;
    label: string;
    description: string;
    payload: Record<string, unknown> | null;
    queues: string;
    topics: string;
};
