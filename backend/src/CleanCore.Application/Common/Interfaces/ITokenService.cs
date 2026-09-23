using CleanCore.Domain.Entities;

namespace CleanCore.Application.Common.Interfaces;

public interface ITokenService
{
    string GenerateAccessToken(User user);

    RefreshToken GenerateRefreshToken();
}
