import { postJson } from '@/services/apiClient';
import type { GenerateStoryInput, Story } from '@/types';

export function generateStory(input: GenerateStoryInput): Promise<Story> {
  // Claude can take a while on longer stories; give it real room.
  return postJson<Story>('/api/v1/stories/generate', input, { timeoutMs: 90_000 });
}
