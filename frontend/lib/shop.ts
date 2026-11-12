/**
 * Where a "buy" button points. An affiliate link wins when a shoe has one;
 * otherwise a plain Google Shopping search for the shoe, which needs no
 * retailer signup and earns nothing, so it isn't marked sponsored.
 */
export interface ShopLink {
  href: string;
  label: string;
  rel: string;
  isAffiliate: boolean;
}

export function shopLink(brand: string, name: string, affiliateUrl: string | null): ShopLink {
  if (affiliateUrl) {
    return { href: affiliateUrl, label: "Shop this shoe", rel: "sponsored noopener", isAffiliate: true };
  }
  const query = name.toLowerCase().startsWith(brand.toLowerCase()) ? name : `${brand} ${name}`;
  return {
    href: `https://www.google.com/search?tbm=shop&q=${encodeURIComponent(`${query} basketball shoes`)}`,
    label: "Find it online",
    rel: "noopener noreferrer",
    isAffiliate: false,
  };
}
