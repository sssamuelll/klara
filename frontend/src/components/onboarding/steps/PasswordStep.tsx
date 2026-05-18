import Step, { type StepProps } from "../Step";

export default function PasswordStep(props: Omit<StepProps, "title" | "children">) {
  return <Step {...props} title="(stub PasswordStep)">stub</Step>;
}
