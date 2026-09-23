using CleanCore.Domain.Common;

namespace CleanCore.Domain.Entities;

public enum Role
{
    User,
    Admin
}

public sealed class User : BaseEntity
{
    public string Email { get; set; } = string.Empty;

    public string PasswordHash { get; set; } = string.Empty;

    public string FirstName { get; set; } = string.Empty;

    public string LastName { get; set; } = string.Empty;

    public Role Role { get; set; } = Role.User;

    public List<RefreshToken> RefreshTokens { get; set; } = [];
}
