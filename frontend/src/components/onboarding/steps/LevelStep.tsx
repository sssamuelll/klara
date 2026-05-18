import Step, { type StepProps } from "../Step";

export default function LevelStep(props: Omit<StepProps, "title" | "children">) {
  return <Step {...props} title="(stub LevelStep)">stub</Step>;
}
