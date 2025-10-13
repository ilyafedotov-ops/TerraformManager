export type ServiceBusPreset = {
    id: string;
    label: string;
    description: string;
    payload: Record<string, any> | null;
    queues: string;
    topics: string;
};
