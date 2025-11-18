export type ProductAnalysisResult = {
  validation: {
    isDetailPage: boolean;
    reason: string;
  };
  productData: null | {
    title: string;
    price_value: string;
    currency: string;
    imageUrl: string;
  };
};

export type ProxyConfig = {
  username: string;
  password: string;
  host: string;
  port: number;
};
