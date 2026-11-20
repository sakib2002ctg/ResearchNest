import type { ConversationInput, Language, ProjectDetail } from "./api";

export function projectConversationInput(project: Pick<ProjectDetail, "id" | "title" | "papers">, language: Language): ConversationInput {
  return {
    title: Array.from(project.title).slice(0, 200).join(""),
    project_id: project.id,
    scope_type: "selected_papers",
    scope_paper_ids: project.papers.slice(0, 50).map((paper) => paper.user_paper_id),
    scope_collection_id: null,
    language,
  };
}
