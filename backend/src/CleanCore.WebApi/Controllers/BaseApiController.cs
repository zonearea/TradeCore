using CleanCore.Domain.Common;
using Microsoft.AspNetCore.Mvc;

namespace CleanCore.WebApi.Controllers;

[ApiController]
public abstract class BaseApiController : ControllerBase
{
    protected IActionResult ToProblem(Error error)
    {
        var status = error.Code switch
        {
            "Validation.Failed" => StatusCodes.Status400BadRequest,
            "User.EmailAlreadyInUse" => StatusCodes.Status409Conflict,
            "User.InvalidCredentials" => StatusCodes.Status401Unauthorized,
            "Auth.InvalidRefreshToken" => StatusCodes.Status401Unauthorized,
            "User.NotFound" => StatusCodes.Status404NotFound,
            _ => StatusCodes.Status400BadRequest
        };

        return Problem(
            statusCode: status,
            title: error.Code,
            detail: error.Message,
            type: "https://tools.ietf.org/html/rfc7807");
    }

    protected IActionResult FromResult<T>(Result<T> result, Func<T, IActionResult> onSuccess)
    {
        if (result.IsFailure || result.Value is null)
        {
            return ToProblem(result.Error);
        }

        return onSuccess(result.Value);
    }
}
