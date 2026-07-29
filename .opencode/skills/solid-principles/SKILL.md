---
name: solid-principles
description: Deep dive into SOLID principles with PHP/TypeScript examples, refactoring patterns, and violation detection
license: MIT
compatibility: opencode
metadata:
  type: architectural
  languages: php, typescript
---

## Single Responsibility Principle (SRP)

**Definition**: A class should have only one reason to change.

### Violation Example
```php
class UserService
{
    public function createUser(array $data): User
    {
        // Validates data
        // Creates user in DB
        // Sends welcome email
        // Logs the action
        // Generates PDF report
    }
}
```

### Refactored
```php
final class UserService
{
    public function __construct(
        private readonly UserValidator $validator,
        private readonly UserRepository $repository,
        private readonly EventDispatcherInterface $dispatcher
    ) {}

    public function createUser(array $data): User
    {
        $this->validator->validate($data);
        $user = $this->repository->create($data);
        $this->dispatcher->dispatch(new UserCreated($user));
        return $user;
    }
}
```

---

## Open/Closed Principle (OCP)

**Definition**: Open for extension, closed for modification.

### Refactored (Strategy Pattern)
```php
interface PaymentGatewayInterface
{
    public function process(float $amount): PaymentResult;
    public function supports(string $type): bool;
}

final class PaymentProcessor
{
    /** @param PaymentGatewayInterface[] $gateways */
    public function __construct(private readonly iterable $gateways) {}

    public function process(string $type, float $amount): PaymentResult
    {
        foreach ($this->gateways as $gateway) {
            if ($gateway->supports($type)) {
                return $gateway->process($amount);
            }
        }
        throw new UnsupportedPaymentTypeException($type);
    }
}
```

---

## Liskov Substitution Principle (LSP)

**Definition**: Subtypes must be substitutable for their base types.

### Refactored
```php
interface ShapeInterface
{
    public function getArea(): int;
}

final class Rectangle implements ShapeInterface
{
    public function __construct(
        private readonly int $width,
        private readonly int $height
    ) {}

    public function getArea(): int
    {
        return $this->width * $this->height;
    }
}

final class Square implements ShapeInterface
{
    public function __construct(private readonly int $side) {}

    public function getArea(): int
    {
        return $this->side * $this->side;
    }
}
```

---

## Interface Segregation Principle (ISP)

**Definition**: Clients shouldn't depend on interfaces they don't use.

### Refactored
```php
interface WorkableInterface { public function work(): void; }
interface FeedableInterface { public function eat(): void; }
interface RestableInterface { public function sleep(): void; }

final class Human implements WorkableInterface, FeedableInterface, RestableInterface
{
    public function work(): void { /* ... */ }
    public function eat(): void { /* ... */ }
    public function sleep(): void { /* ... */ }
}

final class Robot implements WorkableInterface
{
    public function work(): void { /* ... */ }
}
```

---

## Dependency Inversion Principle (DIP)

**Definition**: Depend on abstractions, not concretions.

### Refactored
```php
interface OrderRepositoryInterface
{
    public function save(Order $order): void;
    public function find(int $id): ?Order;
}

interface MailerInterface
{
    public function send(string $to, string $subject, string $body): void;
}

final class OrderService
{
    public function __construct(
        private readonly OrderRepositoryInterface $repository,
        private readonly MailerInterface $mailer
    ) {}

    public function placeOrder(Order $order): void
    {
        $this->repository->save($order);
        $this->mailer->send(
            $order->getCustomerEmail(),
            'Order Confirmation',
            'Your order has been placed.'
        );
    }
}
```

---

## Quick Detection Checklist

| Principle | Smell | Fix |
|-----------|-------|-----|
| SRP | Class has multiple `and` in description | Split into focused classes |
| OCP | Adding features requires modifying existing code | Use interfaces/strategy |
| LSP | Subclass throws unexpected exceptions | Composition over inheritance |
| ISP | Class implements methods it doesn't need | Split interface |
| DIP | `new` keyword for dependencies | Constructor injection |
