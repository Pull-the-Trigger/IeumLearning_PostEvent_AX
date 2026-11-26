import { SurveyForm } from "@/components/survey-form";
import { getSurveyDefinitionByToken } from "@/lib/survey-data";

export default async function SurveyPreviewRoute({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const definition = getSurveyDefinitionByToken(token);
  if (!definition) return <main className="survey-shell"><div className="survey-error-page"><h1>설문 링크를 찾을 수 없습니다</h1></div></main>;
  return <SurveyForm definition={definition} preview />;
}
