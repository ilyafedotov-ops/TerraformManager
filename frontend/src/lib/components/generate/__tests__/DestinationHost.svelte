<script lang="ts">
    import DestinationStep from '../DestinationStep.svelte';

    export let props: Record<string, unknown>;
    export let onEvent: ((payload: { type: string; detail?: Record<string, unknown> }) => void) | null = null;

    const forward = (event: CustomEvent) => {
        onEvent?.({ type: event.type, detail: event.detail });
    };
</script>

<DestinationStep
    {...props}
    on:projectChange={forward}
    on:toggleAutoSave={forward}
    on:assetNameChange={forward}
    on:assetDescriptionChange={forward}
    on:assetTagsChange={forward}
    on:save={forward}
    on:goToReview={forward}
    on:goToConfigure={forward}
/>
