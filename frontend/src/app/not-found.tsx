import { LinkButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";

export default function NotFound() {
  return (
    <EmptyState
      title="That page isn't here"
      body="The link may be old, or the address may have a typo. Let's get you back to the homes."
      actions={
        <>
          <LinkButton href="/explore">Explore homes</LinkButton>
          <LinkButton href="/" variant="secondary">Back to home</LinkButton>
        </>
      }
    />
  );
}
