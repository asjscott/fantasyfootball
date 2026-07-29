import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/predictions", label: "Predictions" },
  { href: "/fixtures", label: "Fixtures" },
];

export function Nav() {
  return (
    <nav className="flex gap-4 border-b border-gray-200 px-6 py-4 text-sm font-medium">
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
