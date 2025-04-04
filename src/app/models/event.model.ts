export interface Event {
    id: number;
    name: string;
    date: string; // Use string for simplicity, Date object is also an option
    location: string;
    description: string;
    price?: number; // Optional price
  }