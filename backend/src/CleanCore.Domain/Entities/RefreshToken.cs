using CleanCore.Domain.Common;

namespace CleanCore.Domain.Entities;

public sealed class RefreshToken : BaseEntity
{
    public string Token { get; set; } = string.Empty;

    public DateTime ExpiresOnUtc { get; set; }

    public DateTime? RevokedOnUtc { get; set; }

    public bool IsActive => RevokedOnUtc is null && ExpiresOnUtc > DateTime.UtcNow;

    public Guid UserId { get; set; }
}
